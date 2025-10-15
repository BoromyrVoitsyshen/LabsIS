using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace OntologyAnimals
{
    public enum RelationType
    {
        IsA,
        PartOf,
        HasProperty,
        Eats,       
        LivesIn     
    }
    public class Relation
    {
        public string Source { get; }
        public RelationType RelationKind { get; }
        public string Target { get; }

        public Relation(string source, RelationType rel, string target)
        {
            Source = source;
            RelationKind = rel;
            Target = target;
        }
    }

    public class KnowledgeBase
    {
        private readonly List<Relation> relations = new();

        public void AddRelation(string source, RelationType relation, string target)
        {
            relations.Add(new Relation(source, relation, target));
        }

        public List<Relation>? FindConnectionPath(string start, string end)
        {
            var visited = new HashSet<string>();
            var stack = new Stack<(string, List<Relation>)>();
            stack.Push((start, new List<Relation>()));

            while (stack.Count > 0)
            {
                var (current, path) = stack.Pop();

                if (!visited.Add(current.ToLower())) continue;

                foreach (var rel in relations.Where(r => string.Equals(r.Source, current, StringComparison.OrdinalIgnoreCase)))
                {
                    var newPath = new List<Relation>(path) { rel };

                    if (string.Equals(rel.Target, end, StringComparison.OrdinalIgnoreCase))
                    {
                        return newPath;
                    }
                    stack.Push((rel.Target, newPath));
                }
            }

            return null;
        }

        public IEnumerable<string> GetAllTerms()
        {
            return relations
                .SelectMany(r => new[] { r.Source, r.Target })
                .Distinct()
                .OrderBy(x => x);
        }

        public Dictionary<string, List<string>> GetCategorizedTerms()
        {
            var allRelations = relations;

            // Автоматично знаходимо терміни за їх роллю у відношеннях
            var properties = allRelations.Where(r => r.RelationKind == RelationType.HasProperty).Select(r => r.Target).Distinct().ToList();
            var habitats = allRelations.Where(r => r.RelationKind == RelationType.LivesIn).Select(r => r.Target).Distinct().ToList();
            var food = allRelations.Where(r => r.RelationKind == RelationType.Eats).Select(r => r.Target).Distinct().ToList();
            var parts = allRelations.Where(r => r.RelationKind == RelationType.PartOf).Select(r => r.Source).Distinct().ToList();

            // Визначаємо, що є групою, а що - конкретною істотою
            var isASources = allRelations.Where(r => r.RelationKind == RelationType.IsA).Select(r => r.Source).ToHashSet();
            var isATargets = allRelations.Where(r => r.RelationKind == RelationType.IsA).Select(r => r.Target).ToHashSet();

            // Істоти - це ті, хто є в ієрархії IsA, але ніколи не є батьківською групою
            var creatures = isASources.Except(isATargets).ToList();
            // Групи - це всі батьківські класи в ієрархії IsA
            var groups = isATargets.ToList();

            var result = new Dictionary<string, List<string>>
    {
        { "CREATURES & SPECIES", creatures },
        { "BIOLOGICAL GROUPS", groups },
        { "ANATOMY & PARTS", parts },
        { "PROPERTIES & ABILITIES", properties },
        { "HABITATS & FOOD", habitats.Concat(food).Distinct().ToList() }
    };

            // Сортуємо списки та видаляємо порожні категорії
            return result
                .Where(kvp => kvp.Value.Any())
                .ToDictionary(kvp => kvp.Key, kvp => kvp.Value.OrderBy(t => t).ToList());
        }
    }


    internal class Program
    {
        static void Main(string[] args)
        {
            var kb = new KnowledgeBase();
 
            kb.AddRelation("Animal", RelationType.IsA, "Living Organism");
            kb.AddRelation("Vertebrate", RelationType.IsA, "Animal");
            kb.AddRelation("Invertebrate", RelationType.IsA, "Animal");
      
            kb.AddRelation("Mammal", RelationType.IsA, "Vertebrate");
            kb.AddRelation("Bird", RelationType.IsA, "Vertebrate");
            kb.AddRelation("Fish", RelationType.IsA, "Vertebrate");
            kb.AddRelation("Reptile", RelationType.IsA, "Vertebrate");  
            kb.AddRelation("Amphibian", RelationType.IsA, "Vertebrate");
    
            kb.AddRelation("Carnivore", RelationType.IsA, "Mammal");
            kb.AddRelation("Primate", RelationType.IsA, "Mammal");
            kb.AddRelation("Herbivore", RelationType.IsA, "Mammal");
  
            kb.AddRelation("Felidae", RelationType.IsA, "Carnivore");  
            kb.AddRelation("Canidae", RelationType.IsA, "Carnivore");  
            kb.AddRelation("Ursidae", RelationType.IsA, "Carnivore");  

            kb.AddRelation("Panthera", RelationType.IsA, "Felidae"); 
            kb.AddRelation("Lion", RelationType.IsA, "Panthera");
            kb.AddRelation("Tiger", RelationType.IsA, "Panthera");
            kb.AddRelation("Jaguar", RelationType.IsA, "Panthera");

            kb.AddRelation("Wolf", RelationType.IsA, "Canidae");
            kb.AddRelation("Fox", RelationType.IsA, "Canidae");

            kb.AddRelation("Eagle", RelationType.IsA, "Bird");
            kb.AddRelation("Snake", RelationType.IsA, "Reptile");
            kb.AddRelation("Frog", RelationType.IsA, "Amphibian");
            kb.AddRelation("Zebra", RelationType.IsA, "Herbivore");
            kb.AddRelation("Deer", RelationType.IsA, "Herbivore");

            kb.AddRelation("Claw", RelationType.PartOf, "Paw");
            kb.AddRelation("Paw", RelationType.PartOf, "Felidae");
            kb.AddRelation("Paw", RelationType.PartOf, "Canidae");
            kb.AddRelation("Fang", RelationType.PartOf, "Snake"); 
            kb.AddRelation("Wing", RelationType.PartOf, "Bird");
            kb.AddRelation("Beak", RelationType.PartOf, "Bird");

            kb.AddRelation("Mammal", RelationType.HasProperty, "Warm-blooded");
            kb.AddRelation("Reptile", RelationType.HasProperty, "Cold-blooded");
            kb.AddRelation("Bird", RelationType.HasProperty, "Ability to fly");
            kb.AddRelation("Lion", RelationType.HasProperty, "Lives in a pride");
            kb.AddRelation("Snake", RelationType.HasProperty, "Venom"); 
            kb.AddRelation("Frog", RelationType.HasProperty, "Metamorphosis");
            kb.AddRelation("Carnivore", RelationType.HasProperty, "Eats meat");

            kb.AddRelation("Lion", RelationType.Eats, "Zebra");
            kb.AddRelation("Wolf", RelationType.Eats, "Deer");
            kb.AddRelation("Fox", RelationType.Eats, "Frog");
            kb.AddRelation("Eagle", RelationType.Eats, "Snake");
            kb.AddRelation("Zebra", RelationType.Eats, "Grass");

            kb.AddRelation("Lion", RelationType.LivesIn, "Savanna");
            kb.AddRelation("Tiger", RelationType.LivesIn, "Jungle");
            kb.AddRelation("Zebra", RelationType.LivesIn, "Savanna");
            kb.AddRelation("Frog", RelationType.LivesIn, "Swamp");
            kb.AddRelation("Wolf", RelationType.LivesIn, "Forest");

            Console.WriteLine("Available terms grouped by category:");
            var categorizedTerms = kb.GetCategorizedTerms();
            PrintCategorizedTerms(categorizedTerms);

            while (true)
            {                      
                Console.Write("Start: ");
                string start = Console.ReadLine()?.Trim() ?? "";
                if (start.ToLower() == "exit") break;

                Console.Write("End: ");
                string end = Console.ReadLine()?.Trim() ?? "";
                if (end.ToLower() == "exit") break;

                if (string.IsNullOrWhiteSpace(start) || string.IsNullOrWhiteSpace(end))
                {
                    Console.WriteLine("Please enter valid terms.\n");
                    continue;
                }

                PrintQuery(kb, start, end);
                Console.WriteLine();
            }
        }
        static void PrintQuery(KnowledgeBase kb, string start, string end)
        {
            Console.WriteLine($"\nIs '{start}' related to '{end}'?");
            var path = kb.FindConnectionPath(start, end);

            if (path != null)
            {
                Console.WriteLine("Yes, path exists:");
                foreach (var rel in path)
                {
                    Console.Write($"{rel.Source} -[{rel.RelationKind}]-> {rel.Target}");
                    if (rel.Target != end) Console.Write(" -> ");
                }
                Console.WriteLine();
            }
            else
            {
                Console.WriteLine("No relation found.");
            }
        }

        static void PrintCategorizedTerms(Dictionary<string, List<string>> categorizedTerms)
        {
            foreach (var category in categorizedTerms)
            {
                var termsList = category.Value;
                if (!termsList.Any()) continue;

                Console.WriteLine($"--- {category.Key} ---");

                const int numberOfColumns = 3;
                int maxLength = termsList.Max(t => t.Length);
                int columnWidth = maxLength + 2; 

                string rowSeparator = "+".PadRight(columnWidth + 1, '-') + "+";
                if (numberOfColumns > 1) rowSeparator = "+" + string.Join("+", Enumerable.Repeat(new string('-', columnWidth), numberOfColumns)) + "+";

                Console.WriteLine(rowSeparator);
                for (int i = 0; i < termsList.Count; i++)
                {
                    string cellContent = $" {termsList[i].PadRight(columnWidth - 1)}";
                    Console.Write($"|{cellContent}");

                    if ((i + 1) % numberOfColumns == 0)
                    {
                        Console.WriteLine("|");
                    }
                }

                int remainingCells = termsList.Count % numberOfColumns;
                if (remainingCells != 0)
                {
                    for (int i = 0; i < numberOfColumns - remainingCells; i++)
                    {
                        Console.Write($"|{new string(' ', columnWidth)}");
                    }
                    Console.WriteLine("|");
                }
                Console.WriteLine(rowSeparator);
                Console.WriteLine();
            }
        }
    }
}

/* Приклади запитів:
Запит:
      * start: `Lion`
      * end: `Felidae`
Очікуваний результат:
    Is 'Lion' related to 'Felidae'?
    ✅ Yes, path exists:
    Lion -[IsA]-> Panthera -> Panthera -[IsA]-> Felidae

Запит:
      * start: `Tiger`
      * end: `Animal`
Очікуваний результат:
    Is 'Tiger' related to 'Animal'?
    ✅ Yes, path exists:
    Tiger -[IsA]-> Panthera -> Panthera -[IsA]-> Felidae -> Felidae -[IsA]-> Carnivore -> Carnivore -[IsA]-> Mammal -> Mammal -[IsA]-> Vertebrate -> Vertebrate -[IsA]-> Animal

Запит:
      * start: `Wolf`
      * end: `Warm-blooded`
Очікуваний результат:
    Is 'Wolf' related to 'Warm-blooded'?
    ✅ Yes, path exists:
    Wolf -[IsA]-> Canidae -> Canidae -[IsA]-> Carnivore -> Carnivore -[IsA]-> Mammal -> Mammal -[HasProperty]-> Warm-blooded

Запит:

      * start: `Lion`
      * end: `Grass`
Очікуваний результат:
    Is 'Lion' related to 'Grass'?
    ✅ Yes, path exists:
    Lion -[Eats]-> Zebra -> Zebra -[Eats]-> Grass

Запит:
      * start: `eagle`
      * end: `ability to fly`
Очікуваний результат:
    Is 'eagle' related to 'ability to fly'?
    ✅ Yes, path exists:
    Eagle -[IsA]-> Bird -> Bird -[HasProperty]-> Ability to fly

Запит:
      * start: `Lion`
      * end: `(натиснути Enter)`
Очікуваний результат:
    ⚠️ Please enter valid terms.

Запит:
      * start: `Fish`
      * end: `Ability to fly`
Очікуваний результат:
    Is 'Fish' related to 'Ability to fly'?
    ❌ No relation found.
*/