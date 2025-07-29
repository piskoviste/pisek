import java.util.Scanner;
import java.util.ArrayList;

public class lib {
    public static ArrayList<Integer> readInput() {
        Scanner scanner = new Scanner(System.in);
        int count = scanner.nextInt();
        ArrayList<Integer> numbers = new ArrayList<Integer>();
        for (int i = 0; i < count; i++) {
            numbers.add(scanner.nextInt());
        }
        return numbers;
    }
}
